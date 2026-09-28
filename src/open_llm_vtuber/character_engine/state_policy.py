"""角色狀態怎麼隨互動改變。

引擎不決定「什麼事會改變角色」——它只提供狀態欄位、提交流程，以及背景的使用者
情緒觀察，規則由 host 定。這個模組就是 Tomoshibi 的規則。

規則只看兩個數字，不看情緒的文字標籤。標籤是模型寫的自由文字，實測同一個模型
會交出「疲倦」「joy」「curiosity」混著來，拿它查表等於每種語言各維護一份詞庫：

- ``valence``：對方心情好不好（-1 到 1）。
- ``stance``：對方怎麼對待角色（-1 敵意、1 友善；不是在對她說話時是 0）。

分成兩個是因為它們的意義不同。對方被老闆罵了一整天來找她說話，心情是負的、
對她卻是友善的——這時候該漲的是信任，不是扣好感。

這裡的數字是起點，要看逐字稿調整。見
docs/superpowers/specs/2026-09-28-character-engine-agent-design.md。
"""

import math
from dataclasses import dataclass
from typing import Any, Mapping, Optional

TRUST_PER_TURN = 0.3  # 持續來往本身就會累積一點信任
FAVORABILITY_PER_WARMTH = 4.0
TRUST_PER_WARMTH = 2.0
TRUST_PER_HOSTILITY = 3.0  # 敵意扣的信任比友善賺的多：信任好建不好修
TRUST_PER_CONFIDING = 1.0

# 低於這個絕對值就當作「沒有明顯傾向」。實測平淡的一輪會給 0.0–0.2。
NOTABLE = 0.3

# 關係階段看信任與好感的平均。由低到高排列。
STAGES = (
    ("stranger", 0.0),
    ("acquaintance", 58.0),
    ("friend", 68.0),
    ("close", 82.0),
)
# 降級要比門檻再低這麼多才發生，否則數值停在門檻附近時每一輪都在升降。
DOWNGRADE_MARGIN = 3.0


@dataclass(frozen=True)
class StateChange:
    """這一輪要套用的變化。None 表示那一項不動。"""

    trust_delta: float
    favorability_delta: float
    emotion: Optional[str]
    relationship_stage: Optional[str]
    applied_observation_id: Optional[str]


def _score(value: Any) -> Optional[float]:
    """讀一個 -1 到 1 的分數；讀不懂就當作沒有。

    bool 是 int 的子類別，True 會被當成 1.0——觀察是模型輸出經過 JSON 來的，
    什麼都可能出現，所以明確擋掉。
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    if math.isnan(number):
        return None
    return max(-1.0, min(1.0, number))


def _unit(value: Any, fallback: float) -> float:
    score = _score(value)
    return fallback if score is None else max(0.0, score)


def _clamp_percent(value: float) -> float:
    return max(0.0, min(100.0, value))


def _stage_index(label: str) -> int:
    for index, (name, _) in enumerate(STAGES):
        if name == label:
            return index
    return 0


def _stage_for(bond: float, current: str) -> Optional[str]:
    current_index = _stage_index(current)
    reached = max(index for index, (_, floor) in enumerate(STAGES) if bond >= floor)
    if reached > current_index:
        return STAGES[reached][0]
    if reached < current_index and bond < STAGES[current_index][1] - DOWNGRADE_MARGIN:
        return STAGES[reached][0]
    # 標籤不在表裡（別的 host 寫的、或手改過檔案）時把它校正回表裡的名字。
    if STAGES[current_index][0] != current:
        return STAGES[reached][0]
    return None


def next_state_change(
    *,
    trust: float,
    favorability: float,
    relationship_stage: str,
    observation: Optional[Mapping[str, Any]],
    applied_observation_id: Optional[str],
    count_turn: bool = True,
) -> StateChange:
    """依目前的狀態與最新一筆使用者情緒觀察，算出要套用的變化。

    ``count_turn=False`` 用在兩輪之間：觀察是背景提交的，通常在下一輪開始前就到了，
    當下就反應才能讓下一句回覆帶著新的心情。那時候不是新的一輪，不加每輪的信任。
    """
    trust_delta = TRUST_PER_TURN if count_turn else 0.0
    favorability_delta = 0.0
    emotion = None
    applied = None

    observation_id = str((observation or {}).get("proposal_id") or "") or None
    if observation and observation_id and observation_id != applied_observation_id:
        # 讀不出分數的觀察（舊版背景工作、模型漏欄位）也算用掉：留著的話
        # 每一輪都會再檢查一次同一筆。
        applied = observation_id
        stance = _score(observation.get("stance"))
        valence = _score(observation.get("valence"))
        intensity = _unit(observation.get("intensity"), 0.5)
        confidence = _unit(observation.get("confidence"), 0.5)

        if stance is not None and valence is not None:
            warmth = stance * intensity * confidence
            if warmth > 0:
                favorability_delta += FAVORABILITY_PER_WARMTH * warmth
                trust_delta += TRUST_PER_WARMTH * warmth
            elif warmth < 0:
                favorability_delta += FAVORABILITY_PER_WARMTH * warmth
                trust_delta += TRUST_PER_HOSTILITY * warmth

            # 敵意最優先；其次看對方難不難過——帶著信任來訴苦的人對她是友善的，
            # 但她該擔心，不是開心（好感照樣在上面漲過了）。
            if stance <= -NOTABLE:
                emotion = "hurt"
            elif valence <= -NOTABLE:
                emotion = "concerned"
                trust_delta += TRUST_PER_CONFIDING * intensity
            elif stance >= NOTABLE:
                emotion = "happy"
            else:
                emotion = "calm"

    bond = (
        _clamp_percent(trust + trust_delta)
        + _clamp_percent(favorability + favorability_delta)
    ) / 2
    return StateChange(
        trust_delta=trust_delta,
        favorability_delta=favorability_delta,
        emotion=emotion,
        relationship_stage=_stage_for(bond, relationship_stage),
        applied_observation_id=applied,
    )
