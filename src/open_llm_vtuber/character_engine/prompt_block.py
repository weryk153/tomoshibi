"""把引擎的狀態、目標、想法寫成系統提示的一段。

引擎自己的 ContextBuilder 也會把狀態寫進提示，但那一版是給引擎的前景用的：英文、
帶數字（trust: 50.0/100），還會把提交流程的編號（proposal_id、base_revision）
原樣印出來。Tomoshibi 的前景不走引擎，所以這一段自己寫，規則是：

- 不放數字。模型看到「信任 72/100」不會比看到「你信任對方」表現得更好，卻會
  把數字念出來。
- 不放引擎內部的編號。
- 用人設的語域。人設一貫用「對方」，而且明文禁止角色提起 AI、系統這類詞；
  背景工作的輸出卻滿是「用戶」「助手」。同一個問題在 memory_core 出現過
  （見 build_consolidation_prompt 的第三輪修正）。
"""

import re
from dataclasses import dataclass
from typing import Optional, Sequence

MAX_GOALS = 3
MAX_THOUGHTS = 2
MAX_ENTRY_CHARS = 120
MOODS = {"happy": "開心", "hurt": "受傷", "concerned": "擔心對方", "calm": "平靜"}
STAGES = {"acquaintance": "認識", "friend": "朋友", "close": "很親近"}

# (低於這個值, 描述)，由低到高；最後一項是其餘全部。中間那一段是 None：沒有
# 傾向就什麼都不說。寫出「談不上信任或不信任」等於替人設補了一句冷淡的話，
# 實測下一輪她就回「我們算是剛認識」。
TRUST_BANDS = (
    (35.0, "你對對方有戒心"),
    (45.0, "你對對方還有些保留"),
    (58.0, None),
    (68.0, "你開始信任對方"),
    (82.0, "你信任對方"),
    (float("inf"), "你非常信任對方"),
)
FAVORABILITY_BANDS = (
    (35.0, "你對對方相當反感"),
    (45.0, "你對對方有點反感"),
    (58.0, None),
    (68.0, "你對對方有些好感"),
    (82.0, "你喜歡和對方相處"),
    (float("inf"), "你非常喜歡對方"),
)

# 長的詞排前面：「使用者」要先於「用者」這類子字串被換掉。英文用 \b 避免
# 動到 username、users 這種字。
_USER_WORDS = re.compile(r"使用者|用戶|用户|\b(?:the\s+)?users?\b", re.IGNORECASE)
_ASSISTANT_WORDS = re.compile(
    r"AI\s*助手|AI\s*助理|助手|助理|\b(?:the\s+)?assistant\b", re.IGNORECASE
)


@dataclass(frozen=True)
class CharacterSnapshot:
    emotion: str
    trust: float
    favorability: float
    relationship_stage: str
    goals: Sequence[str] = ()
    thoughts: Sequence[str] = ()


def in_world(text: str, character_name: str) -> str:
    """把背景工作的用語換成人設的語域。"""
    text = _USER_WORDS.sub("對方", text)
    return _ASSISTANT_WORDS.sub(character_name or "你", text)


def _band(value: float, bands) -> Optional[str]:
    for ceiling, description in bands:
        if value < ceiling:
            return description
    return bands[-1][1]


def _entries(items: Sequence[str], limit: int, character_name: str) -> list[str]:
    seen: list[str] = []
    for item in items:
        text = " ".join(in_world(str(item), character_name).split())
        if not text or text in seen:
            continue
        if len(text) > MAX_ENTRY_CHARS:
            text = text[:MAX_ENTRY_CHARS].rstrip() + "…"
        seen.append(text)
        if len(seen) == limit:
            break
    return seen


def _state_lines(snapshot: CharacterSnapshot) -> list[str]:
    lines = []
    mood = MOODS.get(snapshot.emotion)
    if mood:
        lines.append(f"- 心情：{mood}")

    stage = STAGES.get(snapshot.relationship_stage)
    feelings = [
        feeling
        for feeling in (
            _band(snapshot.trust, TRUST_BANDS),
            _band(snapshot.favorability, FAVORABILITY_BANDS),
        )
        if feeling
    ]
    sentences = [f"你和對方的關係：{stage}"] if stage else []
    if feelings:
        sentences.append("，".join(feelings))
    if sentences:
        lines.append("- " + "。".join(sentences) + "。")
    return lines


def build_engine_block(snapshot: CharacterSnapshot, *, character_name: str) -> str:
    """組出系統提示的那一段；沒有值得說的內容時回傳空字串。"""
    sections = []

    state = _state_lines(snapshot)
    if state:
        sections.append(
            "## 你此刻的狀態（隨互動累積；照你的個性自然流露，不要把這段文字說出來）\n"
            + "\n".join(state)
        )

    goals = _entries(snapshot.goals, MAX_GOALS, character_name)
    if goals:
        sections.append(
            "## 你最近放在心上的事（有機會就自然地接著做，不要逐條宣告）\n"
            + "\n".join(f"- {goal}" for goal in goals)
        )

    thoughts = _entries(snapshot.thoughts, MAX_THOUGHTS, character_name)
    if thoughts:
        sections.append(
            "## 你最近的體會（只是參考，不要複述）\n"
            + "\n".join(f"- {thought}" for thought in thoughts)
        )

    return "".join(f"\n\n{section}" for section in sections)
