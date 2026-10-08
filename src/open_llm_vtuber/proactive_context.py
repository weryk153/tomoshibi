"""Per-session context for natural, non-repetitive proactive speech.

Proactive triggers are synthetic instructions, not real user messages.  They must
not pollute the normal chat memory, but the model still needs to know what it
recently said proactively or it will produce the same generic opener each time.
This module keeps a small in-memory rolling window for that purpose.
"""

from collections import OrderedDict, deque
import re
from typing import Deque


MAX_RECENT_PROACTIVE = 6
MAX_RECENT_CHARS = 2000
MAX_PROACTIVE_CONTEXTS = 64


_recent_by_session: OrderedDict[tuple[str, str], Deque[str]] = OrderedDict()


def _clip_preserving_ends(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    separator = " … "
    available = limit - len(separator)
    head_chars = available * 2 // 3
    tail_chars = available - head_chars
    return f"{text[:head_chars]}{separator}{text[-tail_chars:]}"


def _session_key(conf_uid: str, client_uid: str) -> tuple[str, str]:
    return (str(conf_uid or ""), str(client_uid or ""))


def proactive_context_uid(history_uid: str | None, client_uid: str) -> str:
    """Use durable history identity when available, falling back to the socket."""
    return str(history_uid or client_uid or "")


def _touch_session(key: tuple[str, str]) -> None:
    if key in _recent_by_session:
        _recent_by_session.move_to_end(key)
    while len(_recent_by_session) > MAX_PROACTIVE_CONTEXTS:
        _recent_by_session.popitem(last=False)


def get_recent_proactive(conf_uid: str, client_uid: str) -> list[str]:
    """Return a copy of the recent proactive lines for one character/session."""
    key = _session_key(conf_uid, client_uid)
    _touch_session(key)
    return list(_recent_by_session.get(key, ()))


def should_force_statement(conf_uid: str, client_uid: str) -> bool:
    """Return whether the previous proactive turn already asked a question."""
    recent = get_recent_proactive(conf_uid, client_uid)
    return bool(recent and ("？" in recent[-1] or "?" in recent[-1]))


def breaks_what_the_host_knows(
    text: str, image_sources: list[str] | None = None
) -> bool:
    """主動開口的一句話，違反只有主機知道的事：畫面上看不到她說的東西（只給了
    螢幕截圖卻說你的表情、說她替你按了按鈕）、她自稱是程式、這個角色不講的話。

    跟重複、客服腔、只應一聲這些不同：把關她說話的引擎看不到截圖是哪裡來的，也
    不知道人設不准她承認自己是程式，所以接了引擎之後這一段仍由主機擋。
    """
    normalized = " ".join(str(text or "").split())
    valid_sources = {
        source for source in (image_sources or []) if source in {"camera", "screen"}
    }
    if valid_sources == {"screen"}:
        unsupported_physical_observations = (
            "眼神",
            "表情",
            "姿勢",
            "盯著",
            "你的眼神",
            "你那眼神",
            "期待的眼神",
            "你的表情",
            "你那表情",
            "你的姿勢",
            "盯著螢幕",
            "看著螢幕發呆",
            "在螢幕前發呆",
            "發呆",
            "傻笑",
            "無精打採",
            "漫不經心",
            "心不在焉",
        )
        if any(phrase in normalized for phrase in unsupported_physical_observations):
            return True

        unsupported_interface_control = (
            "強制按下",
            "替你按",
            "幫你按",
            "我會按下",
            "我已經按",
            "我剛才按",
            "被我悄悄改寫",
            "我已經改寫",
            "我剛才改寫",
            "我偷偷改寫",
            "關掉你的 Chrome",
            "把你的桌面背景換",
        )
        if any(phrase in normalized for phrase in unsupported_interface_control):
            return True
        if re.search(
            r"我剛才.{0,16}(?:系統後臺|按鈕|介面).{0,16}(?:玩|改|動)",
            normalized,
        ):
            return True
        if re.search(r"\d+\s*/\s*\d+", normalized) and any(
            phrase in normalized
            for phrase in (
                "抽光",
                "抽走",
                "已無庫存",
                "沒有庫存",
                "沒庫存",
                "最後一張",
                "只剩一點",
                "只剩殘渣",
            )
        ):
            return True
        if any(
            phrase in normalized
            for phrase in ("下一秒就會消失", "馬上就會消失", "可能就被人搶光")
        ):
            return True
        if any(
            phrase in normalized
            for phrase in (
                "你自己選擇了",
                "你想逃避現實",
                "你在逃避現實",
                "你根本沒想過",
            )
        ):
            return True

        # A single desktop frame can show source text and old log lines, but it
        # cannot establish runtime causality. Keep direct observations/persona
        # reactions while dropping sentences that turn visible technical text
        # into an unverified diagnosis.
        technical_visual_reference = bool(
            re.search(
                r"(?:畫面|終端機?|程式碼|原始碼|那行|DEBUG|logger|"
                r"init_|agent_engine|system_prompt|TTS|AgentFactory)",
                normalized,
                flags=re.IGNORECASE,
            )
        )
        unsupported_diagnostic_claim = bool(
            re.search(
                r"(?:這代表|這證明|根本(?:沒有|沒能|沒|連)|"
                r"已經(?:跑完|執行完|成功)|成功執行|"
                r"卡(?:住|在)|空轉|(?:BUG|bug|錯誤)(?:原因|就是|在|嗎|！|!))",
                normalized,
            )
        )
        static_frame_claims_motion = bool(
            re.search(
                r"(?:終端機?|DEBUG|日誌).{0,16}(?:一直|正在|持續).{0,8}"
                r"(?:跳動|滾動|更新)",
                normalized,
                flags=re.IGNORECASE,
            )
        )
        if (
            technical_visual_reference and unsupported_diagnostic_claim
        ) or static_frame_claims_motion:
            return True

    # 自稱程式／AI 的自我說明。主動發言沒有使用者的提問要答，所以這種句子一定是
    # 自己冒出來的——實測「畢竟我的程式碼可沒你畫出來的東西那麼有靈魂」。persona
    # 已經逐字禁過「只是個 AI」，9B 照樣講，散文規則壓不住，這裡直接擋掉再重生成。
    #
    # 只綁「自稱」，不綁「談論」：她會看著螢幕聊使用者的程式碼，那是正常話題。
    # 身分提問要照 persona 誠實回答，但那走的是一般回覆，不會經過這個過濾器。
    if re.search(
        r"我(?:的|寫的)(?:程式碼|程式碼庫|代碼|原始碼|source\s*code)",
        normalized,
        flags=re.IGNORECASE,
    ):
        return True
    if re.search(
        r"我(?:這種|這個|只|不過|就)?\s*(?:是|算是)?\s*(?:一?個|一?種)?\s*"
        r"(?:AI|A\.I\.|人工智慧|人工智能|人工人格|程式碼|代碼|程序|機器人|"
        # 「程式」單獨出現才算自稱；「我是程式設計的門外漢」講的是領域不是自己。
        r"演算法|複製品|數位存在|程式(?!設計|語言|開發|員|師|庫))",
        normalized,
        flags=re.IGNORECASE,
    ):
        return True

    proactive_only_phrases = (
        "最近有什麼新鮮事",
        "工作還順利嗎",
        "我會調整我的",
        "我會改進我的",
        "把剛才那句話還原",
        "這句話其實是讓我",
        "這句話的意思是把選擇",
        "失敗者才會說的藉口",
        "失敗者的藉口",
        "自以為是的說法",
        "可笑到讓人",
    )
    return any(phrase in normalized for phrase in proactive_only_phrases)


def record_proactive_response(
    conf_uid: str,
    client_uid: str,
    response: str,
) -> None:
    """Remember a completed proactive response without adding it to chat memory."""
    normalized = " ".join(str(response or "").split())
    if not normalized:
        return

    key = _session_key(conf_uid, client_uid)
    recent = _recent_by_session.setdefault(key, deque(maxlen=MAX_RECENT_PROACTIVE))
    recent.append(_clip_preserving_ends(normalized, MAX_RECENT_CHARS))
    _touch_session(key)


def clear_proactive_context(conf_uid: str, client_uid: str) -> None:
    """Clear one session (primarily for lifecycle cleanup and tests)."""
    key = _session_key(conf_uid, client_uid)
    _recent_by_session.pop(key, None)


# 「你沒回話時：等你」（character_config.proactive_when_unanswered: wait）。前端照設定的
# 秒數一直送觸發，這裡決定這一次開不開口：她沒人回的話一次比一次等得久（沒回 n 次
# 就跳過 2^n - 1 次觸發，也就是等 2^n 倍），連續 WAIT_GIVE_UP 次沒回就不再開口，
# 等對方說話（引擎的 unanswered_remarks 歸零）再從頭算。
WAIT_GIVE_UP = 3
_skipped: OrderedDict[tuple[str, str], int] = OrderedDict()


def wait_allows_speaking(key: tuple[str, str], unanswered: int) -> bool:
    """這次觸發她開不開口（等你模式）。``unanswered`` 是她上次之後沒人回的次數。"""
    if unanswered <= 0:
        _skipped.pop(key, None)
        return True
    if unanswered >= WAIT_GIVE_UP:
        return False
    skipped = _skipped.get(key, 0)
    if skipped < 2**unanswered - 1:
        _skipped[key] = skipped + 1
        _skipped.move_to_end(key)
        while len(_skipped) > MAX_PROACTIVE_CONTEXTS:
            _skipped.popitem(last=False)
        return False
    _skipped.pop(key, None)
    return True
