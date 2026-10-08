"""表情與動作交給背景模型挑（character_config.expression_source: background）。

預設（tags）是主模型在台詞裡帶 [joy] 這類標籤，前端照標籤做表情。代價是系統
提示要解釋標籤、標籤偶爾漏進台詞、小模型常忘記帶。background 模式下系統提示不教
標籤（service_context.construct_system_prompt），改成每一句送 TTS 的同時問引擎：
這個模型有的表情與動作交給 ``companion.reply_actions``（引擎 1.3.0 起），引擎用她的
心情、前一句與這句，叫它的背景模型挑。挑選本身（提示、讀 JSON、一次一句、語氣）
都在引擎；這裡只管 Tomoshibi 這一側：從 Live2D／VRM 模型做出清單與「心情→表情」
對照，把挑到的放進這句的 actions（apply_pick），以及聲音等多久（GRACE_SECONDS）。

聲音不等它：一句一句照順序挑（講這句時挑下一句）。合成好了挑選還沒好，至少再等
GRACE_SECONDS（沒聲音的句子 SILENT_GRACE_SECONDS）；前面的句子還在念的話，可以
等到前面念完前 LEAD_SECONDS。再沒好這句就不帶表情，挑選取消、換下一句。她自己
還是寫了標籤的話以標籤為準。

語氣（GPT-SoVITS 的 emotion_refs）：引擎的 voice()——這則回覆第一個挑到的表情，還
沒有就用她的心情經 mood_faces 對到的表情。

沒設背景模型、或引擎太舊沒有 reply_actions 時，這個模式不成立：提示照舊教標籤、也
不挑（uses_background_expressions），免得選了 background 卻落得一個表情都沒有。
空檔的臉（心情）不歸這裡管。
"""

from __future__ import annotations

import asyncio
from typing import Any, Mapping, Optional

from .background_llm import background_client

SOURCES = ("tags", "background")
GRACE_SECONDS = 0.3  # 合成好了，挑選至少再等這麼久
# 前面的句子還在念時，這句的挑選可以等到前面快念完（提早這麼久送出）
LEAD_SECONDS = 0.5
SILENT_GRACE_SECONDS = 1.0  # 沒聲音的句子（*歪頭*）沒有合成時間可以並行，多等一點

# 引擎的心情詞 → 這個模型的表情（emotionMap 的鍵）；跟前端空檔的臉同一份
# （frontend-src/src/renderer/src/avatar/mood.ts 的 KEYWORDS／FALLBACKS）。
MOOD_KEYWORDS = {
    "neutral": None,
    "happy": "joy",
    "sad": "sadness",
    "angry": "anger",
    "surprised": "surprise",
    "embarrassed": "embarrassed",
    "calm": "relaxed",
    "worried": "sadness",
}
MOOD_FALLBACKS = {"embarrassed": ["joy"], "relaxed": ["neutral"]}


def mood_faces(expressions) -> dict[str, str]:
    """引擎的每個心情用這個模型的哪個表情；模型沒有的心情不列。"""
    have = set(expressions)
    faces = {}
    for mood, keyword in MOOD_KEYWORDS.items():
        if keyword is None:
            continue
        for candidate in [keyword, *MOOD_FALLBACKS.get(keyword, [])]:
            if candidate in have:
                faces[mood] = candidate
                break
    return faces


def avatar_choices(live2d_model: Any) -> Optional[Any]:
    """這個模型給引擎挑的清單（AvatarChoices）；沒得挑、或引擎太舊是 None。"""
    try:
        from ai_character_engine.companion import AvatarChoices
    except ImportError:
        return None
    if live2d_model is None:
        return None
    emo_map = dict(getattr(live2d_model, "emo_map", None) or {})
    motion_map = dict(getattr(live2d_model, "motion_map", None) or {})
    # 一個表情沒得對比（只有 neutral）；跟提示的門檻同一條（construct_system_prompt）。
    expressions = list(emo_map) if len(emo_map) >= 2 else []
    motions = {
        key: str((value or {}).get("label") or "") if isinstance(value, Mapping) else ""
        for key, value in motion_map.items()
    }
    if not expressions and not motions:
        return None
    return AvatarChoices(
        expressions=expressions, motions=motions, mood_faces=mood_faces(expressions)
    )


def uses_background_expressions(character: Any) -> bool:
    """這個角色的表情真的由背景模型挑：選了 background、對話交給引擎、引擎挑得了
    （1.3.0 起），而且有背景模型。"""
    if getattr(character, "expression_source", "tags") != "background":
        return False
    agent = getattr(
        getattr(character, "agent_config", None), "conversation_agent_choice", None
    )
    if (agent or "character_engine_agent") != "character_engine_agent":
        return False
    try:
        from ai_character_engine.companion import AvatarChoices  # noqa: F401
    except ImportError:
        return False
    return background_client(character, max_tokens=80, timeout_seconds=6.5) is not None


class EnginePicker:
    """一則回覆的挑選器（引擎的 ReplyActions）在 Tomoshibi 這一側的樣子。"""

    def __init__(self, actions: Any) -> None:
        self._actions = actions
        # 一句挑完才挑下一句，照順序排隊（引擎遇到正在挑會直接回 None）；
        # 不等了的那句由 tts_manager 取消，排隊中的就不會再問。
        self._turn = asyncio.Lock()

    async def ask(self, line: str) -> Optional[dict]:
        """這句挑到的 {"expression", "motion", "intensity"}；挑不到是 None。"""
        try:
            await self._turn.acquire()
        except asyncio.CancelledError:
            # 排隊時就不等了：這句沒問，但它還是下一句的「前一句」。
            skip = getattr(self._actions, "skip", None)
            if callable(skip):
                skip(line)
            raise
        try:
            picked = await self._actions.pick(line)
        finally:
            self._turn.release()
        if picked is None:
            return None
        return {
            "expression": picked.expression,
            "motion": picked.motion,
            "intensity": picked.intensity,
        }

    def voice_emotion(self) -> Optional[str]:
        """這句的語氣（emotion_refs 的鍵）；引擎的 voice()。"""
        try:
            return self._actions.voice()
        except Exception:
            return None


def picker_for(
    character: Any, live2d_model: Any, agent: Any = None
) -> Optional[EnginePicker]:
    """這一則回覆用的挑選器；tags 模式、沒有背景模型、模型沒得挑、agent 不是
    引擎（或引擎太舊）時是 None。"""
    if not uses_background_expressions(character):
        return None
    choices = avatar_choices(live2d_model)
    if choices is None:
        return None
    reply_actions = getattr(agent, "reply_actions", None)
    if not callable(reply_actions):
        return None
    actions = reply_actions(choices)
    if actions is None or not getattr(actions, "can_pick", False):
        return None
    return EnginePicker(actions)


def apply_pick(actions: Any, picked: Optional[Mapping], live2d_model: Any) -> Any:
    """挑到的放進這句的 actions；她自己寫了標籤的那一項不蓋掉。

    換成前端要的形狀（表情索引、動作的 group/index 或 clip）交給模型自己的
    extract_*，跟標籤走同一條路。
    """
    if not picked or live2d_model is None:
        return actions
    from .agent.output_types import Actions

    actions = actions if actions is not None else Actions()
    expression, motion = picked.get("expression"), picked.get("motion")
    intensity = float(picked.get("intensity", 1.0))
    if expression and not actions.expressions:
        tag = f"[{expression}:{intensity}]"
        found = live2d_model.extract_emotion(tag)
        if found:
            actions.expressions = found
            actions.expression_intensities = live2d_model.extract_emotion_intensities(
                tag
            )
    if motion and not actions.motions:
        found = live2d_model.extract_motions(f"[{motion}]")
        if found:
            actions.motions = found
    return actions
