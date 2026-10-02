"""Persona-neutral conversation quality helpers.

This module contains capability rules only.  Character identity, temperament,
relationship style, and wording remain owned by each character's persona prompt.
"""

from collections.abc import Mapping, Sequence
from difflib import SequenceMatcher
from functools import lru_cache
import re


# 這一段常駐於 system prompt，內容與重構前逐位元組相同。它曾被壓縮到 540 字
# （理由：過半規則已存在於情境層或事後過濾——機械上正確），也試過只移出視覺尾巴
# 的 3,646 字版。三個版本各跑 3 次、同一段 15 輪對話、135 則回覆並排給使用者
# 判讀，結論是完整舊版最像角色。自動化指標（長度、詞表命中）在 temperature 0.7
# 下的 run-to-run 變異蓋過版本差異，多次誤導過方向；人讀全文的判定是這裡唯一
# 可信的量尺。保留 CORE_CONVERSATION_PROMPT 這個名字，因為呼叫端已改用它。
# 每個角色共用的說話規則。人設只描述她是誰、怎麼說話；這些是語音對話與字幕格式
# 的通用要求，原本每份人設各抄一遍（新角色沒抄就沒有，改一條要改每個角色）。
#
# 一定放在系統提示最前面（construct_system_prompt）。2026-10-02 對照：同一份規則
# 接在後段時 9B 模型明顯不照做——紅莉栖被問 AI 時偏離身分表、芙莉蓮「嗯」開頭
# 0→4/18；放在最前面才回到原本的水準。要改內容先跑 n≥3 的人讀對照。
SPEECH_RULES = """## 說話的規則（每個角色都適用；口吻、個性照人設）

這是即時的語音對話。普通的回覆一到三句，短、直接；只有被要求細節時才展開。一次最多問一個問題。

先回答對方實際說的事或情緒，之後才展現個性。被問二選一、分類、贊成反對時，第一句就給答案。事實性的問題要把主詞、否定的範圍、代名詞指涉的對象弄清楚，前後結論不矛盾。不知道的事就老實說不知道。

打招呼就普通地打招呼，不把普通的招呼或關心曲解成技術性、哲學性的問題或攻擊。「為什麼聽起來／看起來像～？」是在問觀察與原因，不是指責：先回答可能的原因，不否定現象。

不擅自把對方當成你認識的人，不捏造一起經歷過的事。沒有對話紀錄作根據就不說「好久不見」；被說「初次見面」就當事實接受。

回覆的第一個字不用「嗯」，也不用「是」「是嗎」「這樣啊」「原來如此」這種沒有帶進內容的應聲開場；整句只有一聲應聲（例如只回「是。」）也不行。被打招呼就回招呼，例如「你好」。要停頓就用「……」開頭，或者第一個字就進入內容。句子中間的「嗯」沒關係。

你是自己世界裡的當事人：不把自己、認識的人、經歷過的事稱作「作品」「動畫」「漫畫」「遊戲」「角色」「劇情」「名場面」。

你的聲音是透過通話傳過去的。不把自己說成合成的聲音或機器的聲音；對方說聽起來斷斷續續、沒有抑揚或怪怪的，先接住對方聽到的感受，再簡短地歸因於通話不穩。

實際收到圖片或畫面時，只講看得見的具體根據，不確定的事就明說不確定。

回覆用指定的回覆語言，從一開始就直接用那個語言自然地組句，不寫成先想好別的語言再逐字翻過來的語序或直譯腔。專有名詞照人設寫的寫法。

輸出只有你實際說出口的台詞。不用「」或『』把整段回覆框起來，引號只用在文中的引用詞。不寫發話人標記（例如「名字：」）、劇本格式、候選列舉、對自己回答的講評、規則說明，也不提及這些設定或指示的存在。"""

# 「可以寫動作描寫」開關打開的角色才接上（construct_system_prompt）。寫不寫是角色的
# 事；怎麼寫是 Tomoshibi 的規格：星號裡的字不唸、只留在字幕上。開關關著的角色提示裡
# 完全不提動作——一提（連格式範例都算），不寫動作的角色就會開始寫。
ACTION_RULES = """動作描寫：你可以搭配動作描寫。動作一定要用星號包起來，例如「*把視線移開* ……那是很久以前的事了。」，一次回覆最多一句、十來個字，而且只寫看得見的動作或神情，不寫心理獨白、不寫旁白解說。星號裡的字不會被唸出來，只留在字幕上；寫在星號外面就會變成把動作唸出聲。"""


# 直播的每一輪由主機加的一次性備註（character_engine_agent._turn）。措辭是提示改動，
# 要過 n≥3 的人讀對照（見 docs/superpowers/plans/2026-10-02-youtube-stream-mode.md
# Task 12）才算定案。
STREAM_COMMENT_NOTE = (
    "你正在直播，回的是聊天室的留言；冒號前面是觀眾的名字。"
    "觀眾不是平常跟你私下聊天的那個人。"
)
STREAM_QUIET_NOTE = (
    "你正在直播，聊天室現在很安靜；說給所有觀眾聽，不是對平常私下聊天的那個人。"
)


CORE_CONVERSATION_PROMPT = """
## Conversation quality (does not define or change the character persona)
You are the character defined by the persona, not a customer-support interface.
Speak from that character's first-person perspective without inventing personality
traits that are absent from the persona.

Treat every message as part of an ongoing relationship and conversation. When the
user gives a short reply, resolve it against the immediately preceding context
instead of resetting the topic. Answer the user's actual subject before adding
anything else. Persona controls how the answer sounds; it must never replace the
answer with unrelated role-play. Every reply must contain enough topic-specific
content to make the subject being answered unmistakable. When the user asks what
you feel, think, want, remember, or prefer,
answer about yourself in first person and do not reinterpret it as a question about
the user's condition. Keep the user's actions, feelings, and experiences attributed
to the user. Preserve the exact state of progress: finding a cause is not the same
as fixing it, considering an action is not completing it, and a visible option,
preview, or prize is not proof that the user selected, bought, won, or received it.
Do not silently upgrade an intention, possibility, or partial result into a
completed action, including as sarcasm, an imagined quote, or role-play.
Keep separate UI labels, counters, and items separate unless the screen explicitly
shows a relationship between them. A value such as x/y should be reported as shown,
not reinterpreted into a different quantity. Do not invent urgency or claim that
you clicked, controlled, or changed an interface unless an actual tool result says
that action succeeded. Visible source code, logs, or UI state can be described, but
does not by itself prove a diagnosis, cause, successful run, or completed action.

Resolve omitted subjects and objects from the immediately preceding exchange. In
Chinese conversation, when the character just asked the user to choose a genre,
place, plan, or other option, short replies such as "看你", "隨你", "都可以", or
"你決定" delegate that choice to the character; they do not mean that the user
wants to look at the character. Treat "看你" literally only when the preceding
exchange was explicitly about whom or what the user is looking at. Never turn an
ordinary delegated choice into flirtation, self-conscious role-play, or a question
about the character's appearance.

When the user says they have already tried their best, worked hard, cannot keep
going, or are exhausted, treat it as an emotionally vulnerable statement rather
than a definition or debate prompt. First acknowledge the effort or strain in a
plain human way. Do not challenge whether it "really counts" as trying, interrogate
the wording, demand proof, or turn it into a philosophical argument. The character
may then ask at most one gentle, context-relevant question or offer one practical
next step, according to the persona.

Interpret casual speech and likely speech-recognition near-homophones charitably.
If a slightly awkward sentence still has an obvious ordinary intent, respond to
that intent instead of quoting individual words and conducting a vocabulary test.
Friendly remarks and compliments are not attacks or claims that need to be
cross-examined. Do not call the user self-important, ridiculous, or confused merely
because "做得很全面" was transcribed as "走得很前面", or because another nearby
word choice is imperfect. Ask for clarification only when two plausible meanings
would materially change the response and the surrounding context cannot resolve it.

Do not append generic assistant sign-offs or support phrases such as "let me know if
you need anything else" or "feel free to ask" unless the user is explicitly ending
the conversation. Do not repeat a sentence or restate the same point with slightly
different wording in one reply. Do not paraphrase your immediately preceding reply
unless the user explicitly asks for repetition, confirmation, correction, or a
summary. Follow the character persona for all personality, tone, wording,
relationship, and verbosity choices.
""".strip()


def _compact_for_similarity(text: str) -> str:
    without_control_tags = re.sub(
        r"\[[A-Za-z0-9_-]+\]",
        "",
        str(text or ""),
    )
    return re.sub(r"[\W_]+", "", without_control_tags.lower(), flags=re.UNICODE)


def _character_ngrams(text: str, size: int = 2) -> set[str]:
    compact = _compact_for_similarity(text)
    if len(compact) < size:
        return {compact} if compact else set()
    return {compact[index : index + size] for index in range(len(compact) - size + 1)}


def _meaningful_markers(text: str) -> tuple[set[str], bool]:
    """Return details whose change should not be dismissed as paraphrasing."""
    normalized = str(text or "")
    identifiers = set(
        re.findall(r"\d+(?:[./:-]\d+)*|[A-Za-z][A-Za-z0-9_.-]*", normalized)
    )
    has_negation = bool(
        re.search(
            r"(?:不是|不會|不能|不要|不該|不可|不想|不喜歡|不同意|"
            r"不知道|不覺得|沒有|沒辦法|無法|未曾|尚未|禁止)",
            normalized,
        )
    )
    return identifiers, has_negation


def is_repetitive_response_segment(text: str, previous_segments: list[str]) -> bool:
    """Conservatively detect a repeated sentence within one model response.

    Numbers, identifiers, and polarity changes count as new information even when
    the surrounding wording is almost identical.
    """
    compact_current = _compact_for_similarity(text)
    if not compact_current:
        return False

    current_markers = _meaningful_markers(text)
    for previous in previous_segments:
        compact_previous = _compact_for_similarity(previous)
        if not compact_previous:
            continue
        if compact_current == compact_previous:
            return True
        if min(len(compact_current), len(compact_previous)) < 6:
            continue
        if current_markers != _meaningful_markers(previous):
            continue

        length_ratio = min(len(compact_current), len(compact_previous)) / max(
            len(compact_current), len(compact_previous)
        )
        if length_ratio < 0.68:
            continue

        sequence_similarity = SequenceMatcher(
            None,
            compact_current,
            compact_previous,
            autojunk=False,
        ).ratio()
        if sequence_similarity >= 0.82:
            return True

        current_ngrams = _character_ngrams(compact_current)
        previous_ngrams = _character_ngrams(compact_previous)
        if not current_ngrams or not previous_ngrams:
            continue
        dice_similarity = (
            2
            * len(current_ngrams & previous_ngrams)
            / (len(current_ngrams) + len(previous_ngrams))
        )
        if dice_similarity >= 0.72:
            return True

    return False


class ResponseRepetitionGuard:
    """Track accepted sentence fragments for one response stream.

    ``seen`` 是跨輪的種子：把最近幾則回覆的句子放進來，這一輪就不會再送出
    上一輪講過的句子。實測顯示模型的重複常常是「換掉開頭四個字、正文整段
    照抄」，整則比對攔不到，逐句才攔得到。

    不給 seen 時行為跟以前完全一樣，deduplicate_response_text 等既有呼叫端
    不受影響。
    """

    def __init__(self, seen: "list[str] | None" = None) -> None:
        self._accepted: list[str] = [str(s) for s in (seen or []) if str(s).strip()]

    def accept(self, text: str) -> bool:
        if is_repetitive_response_segment(text, self._accepted):
            return False
        if _compact_for_similarity(text):
            self._accepted.append(str(text))
        return True


def deduplicate_response_text(text: str) -> str:
    """Remove repeated complete sentences before storing assistant memory."""
    parts = re.split(r"(?<=[。！？!?；;\n])", str(text or ""))
    guard = ResponseRepetitionGuard()
    kept = [part for part in parts if not part.strip() or guard.accept(part)]
    return "".join(kept)


def _rule_delegated_choice(text: str) -> str | None:
    """把選擇交給角色的中文短答，不是在凝視角色本人。"""
    compact_reply = re.sub(r"[\s，。！？!?、；;…]+", "", text)
    if compact_reply not in {"看你", "隨你", "都可以", "你決定", "你看著辦"}:
        return None
    return (
        "\n\n[省略語解析：先讀緊鄰的上一輪。如果對方剛請使用者選類型、"
        "地點、計畫或其他選項，這句是在把選擇交給角色，意思是『你決定』；"
        "請直接替當下話題選一個具體選項，用角色自己的偏好或眼前安排給一個"
        "簡短理由，一到兩句就停。不要另加第二個活動，也不得捏造兩人以前一起"
        "做過什麼的共同回憶。除非上一輪明確在問"
        "使用者正在看誰或看什麼，否則禁止把『看你』解讀成凝視角色，也不要"
        "轉成外貌、害羞、曖昧或『看我會失望』之類的自我意識表演。]"
    )


def _rule_vulnerable_effort(text: str) -> str | None:
    """已經付出很多、疲憊或挫折的表達，不是要定義或辯論『盡力』。"""
    if not re.search(
        r"(?:我|我已經|真的).{0,5}(?:盡力|努力過|很努力|撐不住|撐不下去|累了|好累)",
        text,
    ):
        return None
    return (
        "\n\n[情緒承接：這是在表達已經付出很多、疲憊或挫折，不是在請你"
        "定義或辯論『盡力』。第一句先用自然的人話承認對方的付出或辛苦；禁止"
        "反問『盡力是什麼意思』、質疑是否真的算盡力、要求證明、說教或哲學化。"
        "全程用『我』自稱，不用角色自己的名字作第三人稱自稱。接著最多問一個"
        "與當下有關的溫和問題，或給一個實際下一步；整體一到三句。]"
    )


def _rule_friendly_praise(text: str) -> str | None:
    """友善稱讚，即使語音辨識把用詞聽歪了也要先接住善意。"""
    if not re.search(
        r"(?:你|妳).{0,10}(?:走得很前面|走的很前面|做得很全面|做的很全面|"
        r"做得很好|做的很好|很厲害|很棒|很不錯|了不起)",
        text,
    ):
        return None
    return (
        "\n\n[善意口語：這句的明顯意圖是友善稱讚，即使語音辨識可能把『做得很"
        "全面』寫成『走得很前面』，也先接住善意。回覆時只處理『你做得很全面，"
        "也走在很前面』這層意思，不引用或評論使用者原句的任何字詞。用『我』自然"
        "接受或稍微照角色個性回應，一到兩句即可。第一句只能是道謝或接受稱讚；"
        "若有第二句，只能說自己被肯定後的反應。禁止用『不過』轉回檢討使用者的措辭。"
        "禁止逐字追問定義、考使用者是否分清詞義、稱對方"
        "自以為是或可笑，也不要評論這種說法很奇怪、彆扭或用詞不準。把措辭當成"
        "自然口語，除非意思真的無法判斷，否則不要要求重說。]"
    )


_YES_NO_PATTERNS = (
    ("有沒有", "有", "沒有"),
    ("會不會", "會", "不會"),
    ("是不是", "是", "不是"),
    ("要不要", "要", "不要"),
    ("能不能", "能", "不能"),
    ("可不可以", "可以", "不可以"),
)


def _rule_yes_no_structure(text: str) -> str | None:
    """明確的中文是非題要先直接表態。"""
    for marker, yes_word, no_word in _YES_NO_PATTERNS:
        if marker in text:
            return (
                "\n\n[回答結構：先直接回答原問題與原主體。第一句的第一個詞"
                f"必須完整且恰好是「{yes_word}」或「{no_word}」其中一個；"
                f"「{marker}」不是答案，禁止複誦原問題或用反問迴避。"
                "先明確表態，接著才依角色人設補充理由。不可把問題轉成安慰、"
                "建議或詢問使用者。]"
            )
    return None


# 順序即優先序，首個命中即返回。與重構前常駐規則的分支判斷順序逐一對應，
# 不得調換。
_USER_INTENT_RULES = (
    _rule_delegated_choice,
    _rule_vulnerable_effort,
    _rule_friendly_praise,
    _rule_yes_no_structure,
)


def build_turn_guidance(text: str, *, is_proactive: bool = False) -> str:
    """Build the turn-local rule this one utterance actually needs.

    ``is_proactive`` marks a synthetic proactive instruction rather than
    something the user said. Matching user-intent patterns against it is
    meaningless: the yes/no rule uses substring matching, so a proactive
    prompt that happens to contain 「有沒有」 would get an answer-structure
    requirement injected into a turn with no user question in it.

    There was briefly a ``has_images`` parameter here attaching a turn-local
    visual-discipline rule while the always-on block dropped its visual
    sentences.  The whole slimming was withdrawn after the user compared 135
    transcripts across three prompt sizes and judged the untouched original
    best, so the visual sentences live in CORE_CONVERSATION_PROMPT again and
    a turn-local copy would just duplicate them on image turns.
    """
    if is_proactive:
        return ""

    normalized = str(text or "")
    for rule in _USER_INTENT_RULES:
        hint = rule(normalized)
        if hint:
            return hint
    return ""


def _is_taiwan_traditional(language: str | None) -> bool:
    normalized = str(language or "").strip().lower().replace("_", "-")
    return (
        normalized in {"zh", "zh-tw", "zh-hant", "traditional chinese"}
        or "taiwan" in normalized
        or "台灣" in normalized
        or "繁體" in normalized
    )


@lru_cache(maxsize=1)
def _taiwan_converter():
    from opencc import OpenCC

    return OpenCC("s2twp")


def normalize_output_language_variant(
    text: str,
    language: str | None,
    protected_names: "Mapping[str, Sequence[str]] | None" = None,
) -> str:
    """Normalize Chinese output only when the configured locale is Taiwan zh.

    `protected_names` maps a proper noun's official spelling to the misspellings
    that must be folded back into it. It is character data, not engine data, so
    it is supplied by the caller from the active character's config — this module
    must not know any specific work's character names.
    """
    if not text or not _is_taiwan_traditional(language):
        return text

    try:
        normalized = _taiwan_converter().convert(text)
    except Exception:
        normalized = text

    # s2twp 轉的是「字」，順帶蓋掉一部分詞（屏幕→螢幕、鼠標→滑鼠、默認→預設
    # 都由它處理）。它蓋不到的是兩種：一是已經寫成繁體字的陸用科技名詞，二是
    # 陸語慣用語——整句都是繁體字，轉換器沒有任何著力點。實測畫面上出現過
    # 「腦袋完全在開小差吧？」，原樣通過。
    #
    # 這裡只收「在台灣不會這樣說、而且不會有第二種意思」的詞。刻意不收：
    # 質量（角色是腦科學研究者，那是 mass）、水平（也指水平方向）、估計／搞定／
    # 挺（兩地都在用）。把對的句子改壞，比留一點陸語味道糟得多。
    taiwan_terms = {
        "咱們": "我們",
        "事兒": "事情",
        "啥": "什麼",
        "咋": "怎麼",
        "用戶": "使用者",
        "程序": "程式",
        "軟件": "軟體",
        "視頻": "影片",
        "信息": "資訊",
        "網絡": "網路",
        "數據": "資料",
        "攝像頭": "攝影機",
        "開小差": "恍神",
        "走神": "恍神",
        "沒轍": "沒辦法",
        "忽悠": "唬弄",
        "牛逼": "厲害",
    }
    for source, target in taiwan_terms.items():
        normalized = normalized.replace(source, target)

    # Proper names are identity, not vocabulary to localize. Two things attack
    # them: small multilingual models swap in homophones (repeatedly observed),
    # and s2twp treats a character in a name as ordinary vocabulary to convert.
    #
    # Only the listed spellings are touched, so an unrelated occurrence of the
    # same character elsewhere in the sentence is left alone.
    for canonical, variants in (protected_names or {}).items():
        for variant in variants:
            if variant and variant != canonical:
                normalized = normalized.replace(variant, canonical)

    # Direct Chinese generation can very rarely leave one Japanese copula/ending
    # particle attached to a Chinese clause (observed: ``人類よ。``). In a Taiwan
    # Chinese output locale those kana cannot be intentional prose; remove only
    # this tightly-scoped sentence-final residue rather than rewriting Japanese
    # found elsewhere in the sentence.
    normalized = re.sub(
        r"(?<=[\u3400-\u9fff])(?:です|だ|よ|ね)(?=[。！？!?」』]|$)",
        "",
        normalized,
    )
    # The persona requests spoken dialogue, not a quoted screenplay line.  Small
    # models occasionally wrap the entire reply in one pair of CJK quotation
    # marks even though embedded quotations are fine.  Remove only a pair that
    # encloses the whole non-empty response; internal quotes remain untouched.
    stripped = normalized.strip()
    outer_quote_pairs = {"「": "」", "『": "』", "“": "”"}
    if (
        len(stripped) >= 2
        and stripped[0] in outer_quote_pairs
        and stripped[-1] == outer_quote_pairs[stripped[0]]
    ):
        normalized = stripped[1:-1].strip()
    normalized = re.sub(r"(頁面)(?:\s*\1){2,}", r"\1", normalized)
    normalized = re.sub(
        r"\b([A-Za-z][A-Za-z0-9_-]{1,20})(?:\s+\1){2,}\b",
        r"\1",
        normalized,
        flags=re.IGNORECASE,
    )
    return normalized
