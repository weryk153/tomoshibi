"""Per-session context for natural, non-repetitive proactive speech.

Proactive triggers are synthetic instructions, not real user messages.  They must
not pollute the normal chat memory, but the model still needs to know what it
recently said proactively or it will produce the same generic opener each time.
This module keeps a small in-memory rolling window for that purpose.
"""

from collections import OrderedDict, deque
from difflib import SequenceMatcher
from collections.abc import Mapping, Sequence
import re
import time
from typing import Deque

from .conversation_quality import (
    is_generic_assistant_boilerplate,
    normalize_output_language_variant,
)


MAX_RECENT_PROACTIVE = 6
MAX_RECENT_CHARS = 2000
MAX_PENDING_CHARS = 4000
MAX_PROACTIVE_CONTEXTS = 64

# A proactive turn has no new user utterance to acknowledge.  Letting a bare
# acknowledgement through makes the character appear to answer its own previous
# question (observed as a standalone ``要。`` bubble), then later proactive turns
# build on that invented answer.  Keep substantive short reactions possible; only
# reject the closed set of acknowledgement/yes-no fragments that add no topic.
_PROACTIVE_ACKNOWLEDGEMENT_FRAGMENTS = {
    "嗯",
    "恩",
    "喔",
    "哦",
    "好",
    "好吧",
    "要",
    "不要",
    "是",
    "不是",
    "對",
    "沒錯",
    "可以",
    "不可以",
    "行",
    "知道了",
    # 同一個是非家族原本漏掉的一半。實測畫面上出現過單獨一顆「沒。」泡泡：
    # 它既不是承接也不是新話題，只是在回答角色自己上一輪的問句。
    "有",
    "沒",
    "沒有",
    "會",
    "不會",
    "能",
    "不能",
}

_recent_by_session: OrderedDict[tuple[str, str], Deque[str]] = OrderedDict()
_pending_by_session: dict[tuple[str, str], str] = {}
# Proactive turns carry skip_memory, so nothing they say ever reaches the agent's
# own memory — which is where the conversation anchor comes from.  Without this
# list the anchor stays frozen on the last real exchange and every proactive turn
# is told to "continue the last concrete thing", i.e. to answer the same question
# again.  Reset by the next real user turn.
# Bounded like the anti-repeat window: the budget below normally caps this at 3,
# but the hand-raise button bypasses the budget, so an unbounded list would be a
# slow leak for a user who keeps pressing it without ever replying. Saturating is
# harmless — every consumer only asks "how many, up to the budget".
_since_user_by_session: dict[tuple[str, str], Deque[str]] = {}
# 即時搜尋冷卻：主動發言的搜尋 pass 每個 session 一段時間內只跑一次，
# 同話題不重搜。value = (monotonic timestamp, query)。
_search_by_session: dict[tuple[str, str], tuple[float, str]] = {}

# 保守預算的核心數字：同 session 兩次搜尋至少間隔這麼久。
SEARCH_COOLDOWN_SECONDS = 15 * 60


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
        evicted_key, _ = _recent_by_session.popitem(last=False)
        _pending_by_session.pop(evicted_key, None)
        _since_user_by_session.pop(evicted_key, None)
        _search_by_session.pop(evicted_key, None)


def get_recent_proactive(conf_uid: str, client_uid: str) -> list[str]:
    """Return a copy of the recent proactive lines for one character/session."""
    key = _session_key(conf_uid, client_uid)
    _touch_session(key)
    return list(_recent_by_session.get(key, ()))


ANCHOR_CHARACTER_PREFIX = "角色："
ANCHOR_USER_PREFIX = "使用者："


def extract_anchor_character_lines(conversation_anchor: str | None) -> list[str]:
    """Pull only the character's own turns out of a proactive conversation anchor.

    The anchor is pasted verbatim into the proactive prompt, and a small model
    will sometimes emit it back instead of continuing from it — producing a
    reply identical to the one it just gave. Feeding these lines to the
    duplicate check is what catches that. The user's turns are deliberately
    left out: quoting what the user just said is normal, wanted behaviour.

    A single turn can span several physical lines, so each block runs until the
    next role prefix.
    """
    blocks: list[str] = []
    current: str | None = None
    for line in str(conversation_anchor or "").splitlines():
        if line.startswith(ANCHOR_CHARACTER_PREFIX):
            if current is not None:
                blocks.append(current)
            current = line[len(ANCHOR_CHARACTER_PREFIX) :]
        elif line.startswith(ANCHOR_USER_PREFIX):
            if current is not None:
                blocks.append(current)
            current = None
        elif current is not None:
            current = f"{current}\n{line}"
    if current is not None:
        blocks.append(current)
    return [block.strip() for block in blocks if block.strip()]


def _anchor_last_user_line_was_answered(conversation_anchor: str | None) -> bool:
    """Whether the anchor's last user turn already has a character reply after it.

    A proactive turn normally fires well after the character finished replying, so
    the user's last message is old news.  Answering it a second time is what
    produced the observed ``嗯……你這樣說我也沒辦法反對啦`` — a reply to a line the
    user sent eight minutes earlier and had already been answered.
    """
    last_role: str | None = None
    for line in str(conversation_anchor or "").splitlines():
        if line.startswith(ANCHOR_USER_PREFIX):
            last_role = "user"
        elif line.startswith(ANCHOR_CHARACTER_PREFIX):
            last_role = "character"
    return last_role == "character"


def should_force_statement(conf_uid: str, client_uid: str) -> bool:
    """Return whether the previous proactive turn already asked a question."""
    recent = get_recent_proactive(conf_uid, client_uid)
    return bool(recent and ("？" in recent[-1] or "?" in recent[-1]))


def _delegated_choice_repair_guidance(
    conversation_anchor: str | None,
) -> str:
    """Return a strong correction for a specific Chinese ellipsis misread.

    ``看你`` commonly means "your choice" after a choice question.  A small
    multilingual model can instead take it literally, answer as if the user is
    staring at the character, and then every proactive turn treats that mistaken
    assistant line as ground truth.  Detect the semantic shape rather than a movie-
    specific sentence so other choices (place, food, plan, etc.) recover too.
    """
    turns: list[tuple[str, str]] = []
    for raw_line in str(conversation_anchor or "").splitlines():
        if raw_line.startswith(ANCHOR_USER_PREFIX):
            turns.append(("user", raw_line[len(ANCHOR_USER_PREFIX) :].strip()))
        elif raw_line.startswith(ANCHOR_CHARACTER_PREFIX):
            turns.append(
                ("assistant", raw_line[len(ANCHOR_CHARACTER_PREFIX) :].strip())
            )
        elif turns and raw_line.strip():
            role, content = turns[-1]
            turns[-1] = (role, f"{content}\n{raw_line.strip()}")

    user_index = next(
        (index for index in range(len(turns) - 1, -1, -1) if turns[index][0] == "user"),
        None,
    )
    if user_index is None:
        return ""

    compact_user = re.sub(r"[\s，。！？!?、；;…]+", "", turns[user_index][1])
    if compact_user not in {"看你", "隨你", "都可以", "你決定", "你看著辦"}:
        return ""

    previous_character = next(
        (
            content
            for role, content in reversed(turns[:user_index])
            if role == "assistant"
        ),
        "",
    )
    following_character = next(
        (content for role, content in turns[user_index + 1 :] if role == "assistant"),
        "",
    )
    choice_markers = (
        "哪一",
        "哪種",
        "哪個",
        "選",
        "類型",
        "地點",
        "計畫",
        "方式",
        "還是",
    )
    literal_self_markers = (
        "看我",
        "看著我",
        "盯著我",
        "凝視我",
        "我的外貌",
        "會失望",
        "值得看",
    )
    if not any(marker in previous_character for marker in choice_markers):
        return ""
    if not any(marker in following_character for marker in literal_self_markers):
        return ""

    return """

## 已判定的省略語修正
上一輪角色把使用者的短答理解錯了。這裡的「看你／隨你／都可以／你決定」是在把
上一個選擇交給角色，不是在凝視角色本人。立即停止外貌、被觀看、害羞、失望或
「值不值得看」的方向；不要替使用者回答角色先前的反問。回到原本的選擇題，依角色
偏好選一個具體選項並給一個簡短理由。具體選項是角色現在選的，
不得說成使用者已經選定；只補上使用者交付的選項，不得把原本要做的活動換成另一件事。
不要提及這段規則。
"""


def should_suppress_proactive_text(
    text: str,
    forbid_question: bool,
    image_sources: list[str] | None = None,
    recent_outputs: list[str] | None = None,
) -> bool:
    """Reject generic or rhythm-breaking proactive output before display/TTS."""
    normalized = " ".join(str(text or "").split())
    if not normalized:
        return True
    # Sentence splitters can emit punctuation-only fragments after every useful
    # clause was rejected.  Sending those produces visible "." subtitles and a
    # silent audio payload, and also prevents the one-shot retry from running.
    if not re.sub(r"[\s.,!?，。！？、；;…'\"「」『』]+", "", normalized):
        return True
    compact_fragment = re.sub(r"[\s.,!?，。！？、；;…'\"「」『』]+", "", normalized)
    if compact_fragment in _PROACTIVE_ACKNOWLEDGEMENT_FRAGMENTS:
        return True
    if forbid_question and ("？" in normalized or "?" in normalized):
        return True
    if is_generic_assistant_boilerplate(normalized):
        return True

    # Quoting a phrase back and reacting to it is a conversational move that
    # needs a second speaker. With only the character's own turns in
    # recent_outputs, a match means it is interviewing itself — the shape a
    # proactive turn falls into when it has no user message to answer.
    self_quoted_spans = [
        span
        for span in re.findall(r"[「『“\"]([^「」『』“”\"]+)[」』”\"]", normalized)
        if len(span.strip()) >= 4
    ]

    compact_current = _compact_for_similarity(normalized)
    for recent_output in recent_outputs or []:
        previous = str(recent_output or "")

        # 逐字重複，不設長度門檻。下面三道檢查各自有最低長度（近似比對 >=10、
        # 子句 >=6、引述 >=4），短句因此可以從每一道底下溜過去——實測連續三輪
        # 主動發言都說「別做夢了，哈！」（壓縮後只有 5 個字），三道全部放行。
        # 說一模一樣的話從來不會是對的，不管它多短。
        compact_previous = _compact_for_similarity(previous)
        if compact_current and compact_current == compact_previous:
            return True
        # 新句子整句逐字落在舊句子裡——最常見的是只把上一則的開頭再說一次。
        # 下面三道檢查都是拿「舊句的子句」去量「新句」的佔比，舊句一長就把佔比
        # 稀釋掉：實測畫面上連著兩顆泡泡，第二顆正好是第一顆的開頭那一句，
        # 子句佔比不足 0.55、近似比對被長度拉低，三道全部放行。
        if (
            len(compact_current) >= 8
            and compact_previous
            and compact_current in compact_previous
        ):
            return True
        if any(span.strip() in previous for span in self_quoted_spans):
            return True
        for clause in re.split(r"[，。！？!?、；;\n]+", previous):
            compact_clause = _compact_for_similarity(clause)
            # Sharing a short phrase is normal when a conversation stays on topic.
            # Reject only when the old clause makes up most of the new sentence.
            if (
                len(compact_clause) >= 6
                and compact_clause in compact_current
                and len(compact_clause) >= len(compact_current) * 0.55
            ):
                return True
        if _is_near_duplicate(normalized, recent_output):
            return True

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


def _compact_for_similarity(text: str) -> str:
    return re.sub(r"[\W_]+", "", str(text or "").lower(), flags=re.UNICODE)


def _character_ngrams(text: str, size: int = 2) -> set[str]:
    compact = _compact_for_similarity(text)
    if len(compact) < size:
        return {compact} if compact else set()
    return {compact[index : index + size] for index in range(len(compact) - size + 1)}


def _is_near_duplicate(current: str, previous: str) -> bool:
    """Catch lightly reworded repeats without blocking a genuine new detail."""
    compact_current = _compact_for_similarity(current)
    compact_previous = _compact_for_similarity(previous)
    if min(len(compact_current), len(compact_previous)) < 10:
        return False

    sequence_similarity = SequenceMatcher(
        None,
        compact_current,
        compact_previous,
        autojunk=False,
    ).ratio()
    if sequence_similarity >= 0.78:
        return True

    current_ngrams = _character_ngrams(compact_current)
    previous_ngrams = _character_ngrams(compact_previous)
    if not current_ngrams or not previous_ngrams:
        return False
    dice_similarity = (
        2
        * len(current_ngrams & previous_ngrams)
        / (len(current_ngrams) + len(previous_ngrams))
    )
    return dice_similarity >= 0.72


def build_proactive_retry_prompt(original_prompt: str) -> str:
    """Strengthen a proactive request after every generated sentence was rejected."""
    return f"""{str(original_prompt or "").rstrip()}

## 重新生成
剛才的候選內容未通過輸出檢查。請重新生成角色發言，必須直接承接最近真實對話
或一項確實可見的畫面事實。只用陳述句，不得包含任何問題或問號；不得聲稱看見
來源畫面以外的事物，也不得增加尚未發生的操作或結果。只輸出角色說的內容。
"""


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
    _pending_by_session[key] = _clip_preserving_ends(normalized, MAX_PENDING_CHARS)
    _since_user_by_session.setdefault(key, deque(maxlen=MAX_RECENT_PROACTIVE)).append(
        _clip_preserving_ends(normalized, MAX_RECENT_CHARS)
    )


def record_suppressed_proactive(
    conf_uid: str,
    client_uid: str,
    response: str,
) -> None:
    """記下「生出來但被擋掉」的主動開口，只為了不要再生一次。

    should_suppress_proactive_text 擋掉的句子原本什麼都不留，而下一輪提示詞的
    「最近已經主動說過的內容，不可重複」是從 _recent_by_session 組出來的——模型
    因此不知道自己剛剛講過那句，於是再生一次，再被擋。實測 44 輪主動開口裡有 24
    輪整輪被擋掉，同一句被重生了三十幾次。被擋掉的句子正是最需要記下來別再講的
    那一句，偏偏只有它不會被記。

    只進防重複清單，其他兩處都不碰：

    - _pending 是「使用者下次真的開口時，告訴角色她剛才說了什麼」的橋。這句從來
      沒說出口，放進去角色會以為自己講過。
    - _since_user 有兩個消費者，都把它當成她說出口的話：consecutive_proactive_turns
      決定要不要收手別再講，proactive_lines_since_user_turn 餵給錨點。沒說出口的
      句子不該讓她提早閉嘴，更不該被當成講過的內容引用。
    """
    normalized = " ".join(str(response or "").split())
    if not normalized:
        return

    key = _session_key(conf_uid, client_uid)
    recent = _recent_by_session.setdefault(key, deque(maxlen=MAX_RECENT_PROACTIVE))
    recent.append(_clip_preserving_ends(normalized, MAX_RECENT_CHARS))
    _touch_session(key)


def note_real_user_turn(conf_uid: str, client_uid: str) -> None:
    """Reset the consecutive-monologue state once the user actually replies.

    The anti-repeat window in ``_recent_by_session`` deliberately survives: it
    stops the same proactive opener coming back later in the session.
    """
    _since_user_by_session.pop(_session_key(conf_uid, client_uid), None)


def note_search_performed(conf_uid: str, client_uid: str, query: str) -> None:
    """Remember that this session just spent its search budget on ``query``."""
    _search_by_session[_session_key(conf_uid, client_uid)] = (
        time.monotonic(),
        str(query or ""),
    )


def search_cooldown_active(conf_uid: str, client_uid: str) -> bool:
    """Whether the proactive search pass should stay quiet this turn."""
    entry = _search_by_session.get(_session_key(conf_uid, client_uid))
    if entry is None:
        return False
    performed_at, _query = entry
    return (time.monotonic() - performed_at) < SEARCH_COOLDOWN_SECONDS


def consecutive_proactive_turns(conf_uid: str, client_uid: str) -> int:
    """上次使用者真的開口之後，她主動說出口的輪數。

    以前這個數字有節流的作用（連續 3 次就閉嘴等回覆），使用者要求拿掉了。現在它只是
    觀測用；真正還在用 _since_user 的是 proactive_lines_since_user_turn——錨點靠它
    把這段期間她講過的話接上去。
    """
    return len(_since_user_by_session.get(_session_key(conf_uid, client_uid), ()))


def proactive_lines_since_user_turn(conf_uid: str, client_uid: str) -> list[str]:
    """The character's own turns that the frozen anchor cannot see."""
    return list(_since_user_by_session.get(_session_key(conf_uid, client_uid), ()))


def consume_pending_proactive(conf_uid: str, client_uid: str) -> str | None:
    """Return the latest proactive remark once, for the user's next real turn."""
    return _pending_by_session.pop(_session_key(conf_uid, client_uid), None)


def clear_pending_proactive(conf_uid: str, client_uid: str) -> None:
    """Drop only the one-turn reply bridge while retaining anti-repeat history."""
    _pending_by_session.pop(_session_key(conf_uid, client_uid), None)


def build_proactive_prompt(
    base_prompt: str,
    conf_uid: str,
    client_uid: str,
    idle_seconds: float | None = None,
    image_sources: list[str] | None = None,
    output_language: str | None = None,
    conversation_anchor: str | None = None,
    verified_visual_facts: str | None = None,
    verified_search_facts: str | None = None,
    protected_names: "Mapping[str, Sequence[str]] | None" = None,
) -> str:
    """Add turn-specific continuation and anti-repetition guidance."""
    recent = get_recent_proactive(conf_uid, client_uid)

    if idle_seconds is not None and idle_seconds < 45:
        timing_guidance = (
            "這次沉默很短，剛才的話題如果還有得聊，延續它通常比較自然；"
            "但如果那件事已經結束了，換個題也沒問題，不要硬撐。"
        )
    else:
        timing_guidance = (
            "隔了一段時間了，延續舊話題或起個新話題都可以，挑此刻比較自然的那個。"
        )

    valid_sources = [
        source for source in (image_sources or []) if source in {"camera", "screen"}
    ]
    if valid_sources:
        source_names = {"camera": "鏡頭", "screen": "桌面"}
        labels = "、".join(
            source_names[source] for source in dict.fromkeys(valid_sources)
        )
        if set(valid_sources) == {"screen"}:
            source_boundary = (
                "這次只有桌面畫面；不能聲稱看見使用者的臉、眼神、表情、姿勢或動作。"
            )
        elif set(valid_sources) == {"camera"}:
            source_boundary = (
                "這次只有鏡頭畫面；不能聲稱看見未出現在鏡頭內的桌面或應用程式內容。"
            )
        else:
            source_boundary = "鏡頭與桌面的觀察要各自有可見依據，不要混淆來源。"
        normalized_visual_facts = str(verified_visual_facts or "").strip()
        visual_intro = (
            f"前置中立視覺步驟已檢查最新的{labels}畫面。下面列出的內容是本輪唯一"
            "可用的畫面事實；此階段沒有原圖，不得補充清單以外的畫面細節。"
            if normalized_visual_facts
            else f"這一輪附有最新的{labels}畫面。先實際檢查圖片。"
        )
        facts_block = (
            f"\n\n## 已驗證的畫面事實\n{normalized_visual_facts}\n"
            if normalized_visual_facts
            else ""
        )
        visual_guidance = (
            f"{visual_intro}若有值得談的具體細節或"
            "相較最近觀察出現的新變化，可以自然接回對話。不要只說『我看到畫面』，"
            "也不要捏造圖片裡沒有的事物。畫面顯示選項、商品、獎品或按鈕，不代表"
            "使用者已經選擇、購買、抽中或按下。"
            "不同欄位或項目的數字不能自行拼成因果；x/y 就照畫面理解，不要改成"
            "另一個數量。沒有實際工具執行結果時，不得聲稱角色能代替使用者按下、"
            "控制或改變介面，也不要捏造『馬上消失』之類的時間壓力。"
            "看見程式碼、終端文字或 DEBUG 訊息，不等於已經證明錯誤原因、執行結果"
            "或功能狀態；沒有畫面證據時要用可能性表達，不能下定論。"
            "先分清楚圖片中的視窗與區域：編輯器原始碼、終端輸出、網頁文字、通知"
            "各自獨立；絕不能把一個區域看到的文字說成另一個區域的輸出。"
            "這是自然主動聊天，不是自動除錯；除非使用者正在要求分析，否則只談"
            "直接可見的事實與角色對它的反應，不要主動宣判程式的錯誤原因或執行成敗。"
            "若要根據畫面主動說話，內容至少要帶一個可核對的具體細節，例如物件、"
            "位置、顏色、數字、專有名稱或介面文字；不能只泛稱整頁的類型。"
            f"{source_boundary}若沒有新資訊，就延續文字話題。{facts_block}"
        )
        final_visual_constraint = source_boundary
    else:
        visual_guidance = "這一輪沒有畫面，不要假裝看見鏡頭或桌面內容。"
        final_visual_constraint = "這一輪沒有畫面，不得聲稱看見任何鏡頭或桌面細節。"

    configured_language = str(output_language or "").strip()
    if configured_language:
        language_guidance = (
            f"最終回答必須全程使用設定的回答語言：{configured_language}。"
            "不要因為使用者文字或圖片中的語言而切換。"
        )
    else:
        language_guidance = "回答語言沿用目前角色設定，不要自行改成其他語言。"

    if should_force_statement(conf_uid, client_uid):
        turn_style_guidance = (
            "上一次主動發言已經問過問題，這次禁止再提問；改成角色自己的"
            "一個具體觀察、看法或反應，讓互動不像訪談。"
        )
        final_question_constraint = (
            "本次輸出不得包含問號（「？」或「?」），也不得使用任何疑問句。"
        )
    else:
        turn_style_guidance = (
            "優先說出角色自己的具體觀察或看法；真的有助於推進時，才在最後問一個問題。"
        )
        final_question_constraint = "本次最多只能有一個問句。"

    # The anchor comes from the agent's memory, and _add_message stores whatever
    # the model produced — it applies strip_stage_performance_tag and
    # deduplicate_response_text but NOT normalize_output_language_variant. So a
    # turn that drifted into Simplified is remembered that way, while the same
    # turn was displayed, spoken and written to history in Traditional. Pasting
    # that mixed-script block back into the prompt shows the model its own past
    # turns in the script it is supposed to have stopped using, which invites it
    # to keep drifting. Normalize on the way in — the real fix belongs in
    # _add_message, but this at least stops the loop feeding itself.
    normalized_anchor = normalize_output_language_variant(
        str(conversation_anchor or "").strip(),
        output_language,
        protected_names,
    )

    # The anchor comes from agent memory, which proactive turns never enter. Left
    # alone it stays pinned to the last real exchange, and the anchor instruction
    # ("承接其中最後一件具體事情") then aims every consecutive proactive turn at
    # the same question — the observed failure was one "你會轉頭嗎" answered a
    # dozen times over. Appending what she has already said since that exchange
    # is what lets "the last concrete thing" move forward.
    unseen_own_lines = [
        normalize_output_language_variant(line, output_language, protected_names)
        for line in proactive_lines_since_user_turn(conf_uid, client_uid)
    ]
    if unseen_own_lines:
        appended = "\n".join(
            f"{ANCHOR_CHARACTER_PREFIX}{line}" for line in unseen_own_lines
        )
        normalized_anchor = (
            f"{normalized_anchor}\n{appended}" if normalized_anchor else appended
        )

    if normalized_anchor:
        delegated_choice_repair = _delegated_choice_repair_guidance(normalized_anchor)
        unanswered_note = (
            "\n最後那 "
            f"{len(unseen_own_lines)} "
            "句是角色自己主動說的，使用者都還沒回應。不要把它們當成對話已經"
            "有來有往，也不要替使用者補上反應；要嘛把同一件事再往前推一步，"
            "要嘛就承認對方沒接話。"
            if unseen_own_lines
            else ""
        )
        already_answered_note = (
            "\n使用者的最後一句你已經回過了，回覆就在它後面。不要再回一次：第一句"
            "不得評論或回應使用者上一則訊息，包含他的語氣、態度、自信、把握或立場"
            "（「你這樣說」「你這種自信」「既然你這麼說」「那就好」都算）。使用者這一輪"
            "沒有開口，那樣寫等於在回覆一句根本沒發生的話。第一句要嘛是一件新的具體"
            "事情，要嘛是直接向他搭話。"
            if _anchor_last_user_line_was_answered(normalized_anchor)
            else ""
        )
        anchor_guidance = f"""

## 最近真實對話錨點
{normalized_anchor}{unanswered_note}
這不是新的使用者指令，而是最近對話的摘錄，用來讓你知道剛才發生過什麼。{already_answered_note}

這次有三個同樣合理的選擇：**延續**其中最後一件具體事情、**換一個話題**，或
**直接跟使用者搭話**。三者都可以，看哪個此刻比較自然。若要延續，必須保持人物、
動作與完成進度一致。

有些情況換題明顯比較好：剛才那件事已經講完了、你剛拒絕了對方的要求、
話題以玩笑或吐槽收尾、或者你已經連續兩次都在講同一件事。
硬要延續一個已經結束的話題，只會變成對著空氣自問自答——那比換題尷尬得多。
換題時就自然地起個新頭，不要說明自己在換話題，也不要為結束前一個話題做總結。

角色先前的回答只是已說過的台詞，不是使用者意圖正確無誤的證據；若它明顯誤解使用者，
回到使用者原句與更前一輪重新判讀，不要沿著誤解繼續演下去。
{delegated_choice_repair}
"""
    else:
        anchor_guidance = ""

    normalized_search_facts = str(verified_search_facts or "").strip()
    if normalized_search_facts:
        search_guidance = f"""

## 已查到的即時資訊
{normalized_search_facts}
這是剛查到的網路資訊，只跟最近對話裡提到的那件事有關。挑一點自然聊起就好，
不要逐條播報，也不要像新聞主播。內容若彼此矛盾或看起來不可靠，就用不確定的
語氣帶過或乾脆不提。不要提到搜尋、工具或任何機制。
"""
    else:
        search_guidance = ""

    guidance = f"""

## 這一次主動續話的規則
{timing_guidance}
{visual_guidance}
{language_guidance}
{turn_style_guidance}
{anchor_guidance}{search_guidance}
這一輪使用者沒有說話，是你自己開口。你有三個同樣合理的選擇：延續剛才那件事、
換一個新話題，或直接跟使用者搭話（叫他一聲、說你此刻的念頭或狀態、問他正在做什麼）。
挑此刻最自然的那一個，不要每次都選延續。
不要用空泛的寒暄開場，例如「最近有什麼新鮮事」、「工作還順利嗎」、
「有什麼想聊的嗎」。不要一次丟出多個話題或多個問題。
你正在直接陪眼前的使用者聊天，不是在撰寫產品建議；不要用「系統偵測」、
「用戶正在」或「工具可以」等第三人稱教學口吻。
分清楚角色與使用者：使用者先前用「我」描述的經歷、動作或感受屬於使用者，
續話時要用「你」承接，不能改寫成角色自己做過或感受到。
如果角色最後一句是問句而使用者還沒回答，主動續話不得用「要／不要／是／不是／好」
替使用者作答，也不得像是角色在回答自己的問題。中文短答「看你／隨你／都可以／你決定」
若接在選擇類問題後，表示把選擇交給角色，不是凝視角色本人；不要延伸成外貌或曖昧話題。
保留事情目前的進度：找到原因不等於已經修好，考慮或準備做也不等於已經完成。
不管延續還是換題，發言都要有具體內容，不能只演人設、說一段換到任何對話
都成立的泛用台詞。
如果你選擇延續：要明確帶到最近對話的一個核心名詞、已確認事實或尚未完成的進度，
不能只用「這個」、「那件事」代替承接。
如果你選擇換題：**直接講新的那件事**，第一句就是新內容，帶一個具體的細節或觀察。
不要說「那我們換個話題」「不聊這個了」之類的宣告，也不要回顧或收尾前一個話題——
真人換話題時不會先報告自己要換，那樣反而把已經結束的東西又拖回來。
不要承諾「我會調整／改進」，也不要問「有什麼可以幫你」；主動發言必須自己
帶入一個新內容，不能把找話題的責任丟回使用者。
只輸出角色要說的話。可以完整展開，但內容必須前後連貫、有新資訊，不要為了拉長
而重複同一觀點；最多一個問句，不解釋規則或分析過程。

## 輸出前最後檢查
{final_question_constraint}
{final_visual_constraint}
如果仍在同一話題，這次至少增加一項先前沒說過的內容：新細節、新理由、新連結、
新的角色反應，或真正能推進事情的下一步。不要只把上一句換同義詞重說。
若桌面或鏡頭和上一輪沒有可確認的新變化，不要再次盤點相同物件、文字、數字或按鈕；
改為承接文字對話，或從已確認的細節提出一個不同且有根據的觀點。
逐字核對最近一則使用者訊息與實際可見畫面；不得增加尚未發生的動作、結果或感受。
角色可以依人設開玩笑或幻想，但必須讓人清楚知道那不是已經發生的現實。
只留下角色真正會自然說出口的內容。
"""

    if recent:
        lines = "\n".join(f"- {item}" for item in recent)
        guidance += f"""

## 最近已經主動說過的內容
{lines}
不可重複上面的觀點、事實、問句或句型。若要繼續同一個話題，必須增加一項具體的
新內容讓它往前推進；如果推不動了——尤其已經連續講過兩次——那就換一個話題，
硬撐著繞同一件事比換題尷尬得多。
"""

    return f"{base_prompt.rstrip()}{guidance}"


def clear_proactive_context(conf_uid: str, client_uid: str) -> None:
    """Clear one session (primarily for lifecycle cleanup and tests)."""
    key = _session_key(conf_uid, client_uid)
    _recent_by_session.pop(key, None)
    _pending_by_session.pop(key, None)
    _since_user_by_session.pop(key, None)
    _search_by_session.pop(key, None)
