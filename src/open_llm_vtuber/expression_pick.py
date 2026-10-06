"""表情與動作交給背景模型挑（character_config.expression_source: background）。

預設（tags）是主模型在台詞裡帶 [joy] 這類標籤，前端照標籤做表情。代價是系統
提示要解釋標籤、標籤偶爾漏進台詞、小模型常忘記帶。background 模式下系統提示不教
標籤（service_context.construct_system_prompt），改成每一句送 TTS 的同時問引擎的
背景模型（background_llm，ASR 還原同一套）：這句、前一句、她現在的心情、這個模型
有的表情與動作 → {"expression", "motion", "intensity"}。不在清單上的丟掉。

跟合成並行（tts_manager），逾時 TIMEOUT_SECONDS 就當沒挑到：聲音不等它。挑到的
放進這句原本的 actions（expressions／motions），走原本的 payload。她自己還是寫了
標籤的話以標籤為準。

沒設背景模型時這個模式不成立：提示照舊教標籤、也不挑（uses_background_expressions），
免得選了 background 卻落得一個表情都沒有。空檔的臉（心情）不歸這裡管。
"""

from __future__ import annotations

import asyncio
import json
import math
import re
import time
from typing import Any, Callable, Mapping, Optional, Sequence

from loguru import logger

from .background_llm import background_client

TIMEOUT_SECONDS = 2.5
MAX_TOKENS = 80
SOURCES = ("tags", "background")

SYSTEM_PROMPT = """\
You direct an animated character's face and body while she speaks. For the line she is saying now, pick the facial expression that fits the feeling of that line, and a gesture only when the line clearly calls for one (a greeting, agreeing, pointing something out); most lines have no gesture. Use the previous line and her current mood only as context: the expression follows the line she is saying now. Pick only from the lists given. intensity is how strongly the expression shows, from 0 (barely) to 1 (fully).
Reply with JSON only:
{"expression": "<one of the expressions, or null>", "motion": "<one of the motions, or null>", "intensity": <0 to 1>}"""

_THINK = re.compile(r"<think>.*?</think>", re.S)
_FENCE = re.compile(r"```(?:json)?")
_NOTHING = {"", "null", "none", "nil", "n/a", "-"}


def _first_object(raw: str) -> Optional[dict]:
    """回覆裡第一個 JSON 物件；思考段、``` 圍欄、後面重複的一份都不管。"""
    body = _FENCE.sub("", _THINK.sub("", raw or "")).strip()
    start = body.find("{")
    if start < 0:
        return None
    try:
        value = json.JSONDecoder().raw_decode(body[start:])[0]
    except ValueError:
        return None
    return value if isinstance(value, dict) else None


def _choice(value: Any, allowed: Sequence[str]) -> Optional[str]:
    if not isinstance(value, str):
        return None
    key = value.strip().strip("[]").strip().lower()
    if key in _NOTHING:
        return None
    return key if key in {str(item).lower() for item in allowed} else None


def _intensity(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 1.0
    if math.isnan(number):
        return 1.0
    return max(0.0, min(1.0, number))


def pick_actions(
    reply: str,
    allowed_expressions: Sequence[str],
    allowed_motions: Sequence[str],
    raw: str,
) -> Optional[dict]:
    """背景模型的回覆 → {"expression", "motion", "intensity"}，只留清單上的。

    reply 是她這句話：空的就什麼都不挑。回覆讀不出一個 JSON 物件就是 None；
    讀得出來但挑的不在清單上，那一項是 None。intensity 夾在 0..1，沒給或不是
    數字就是 1（跟標籤沒寫強度一樣）。
    """
    if not (reply or "").strip():
        return None
    data = _first_object(raw)
    if data is None:
        return None
    return {
        "expression": _choice(data.get("expression"), allowed_expressions),
        "motion": _choice(data.get("motion"), allowed_motions),
        "intensity": _intensity(data.get("intensity")),
    }


def _current_mood(message: Optional[Mapping]) -> Optional[str]:
    """character_mood 的訊息 → 「joy (0.42)」；強度照半衰期淡到現在。"""
    if not isinstance(message, Mapping) or not message.get("mood"):
        return None
    try:
        intensity = float(message.get("intensity", 0.0))
        half_life = float(message.get("half_life") or 0.0)
        updated_at = float(message.get("updated_at") or 0.0)
    except (TypeError, ValueError):
        return str(message["mood"])
    if half_life > 0 and updated_at > 0:
        intensity *= 0.5 ** (max(0.0, time.time() - updated_at) / half_life)
    return f"{message['mood']} ({intensity:.2f})"


class ExpressionPicker:
    """一則回覆裡逐句問背景模型。ask 本身不丟例外：失敗、逾時都是 None。"""

    def __init__(
        self,
        *,
        client: Any,
        expressions: Sequence[str],
        motions: Mapping[str, str],
        mood: Callable[[], Optional[Mapping]] = lambda: None,
        timeout_seconds: float = TIMEOUT_SECONDS,
    ) -> None:
        self.client = client
        self.expressions = list(expressions)
        # 動作的關鍵字 → 描述（motionMap 的 label，沒有就空字串）。
        self.motions = dict(motions)
        self.mood = mood
        self.timeout_seconds = timeout_seconds

    def messages(self, line: str, previous: str) -> list[dict]:
        try:
            mood = _current_mood(self.mood())
        except Exception as error:
            logger.debug(f"[expression] mood not read ({type(error).__name__})")
            mood = None
        motions = ", ".join(
            f"{key} ({label})" if label else key for key, label in self.motions.items()
        )
        user = "\n".join(
            [
                f"Expressions: {', '.join(self.expressions) or '(none)'}",
                f"Motions: {motions or '(none)'}",
                f"Her mood: {mood or 'unknown'}",
                f"Previous line: {previous.strip() or '(none)'}",
                f"Line: {line.strip()}",
            ]
        )
        return [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user},
        ]

    async def ask(self, line: str, *, previous: str = "") -> Optional[dict]:
        if not line.strip():
            return None
        started = time.monotonic()
        try:
            raw = await asyncio.wait_for(
                self.client.complete(self.messages(line, previous)),
                timeout=self.timeout_seconds,
            )
        except asyncio.TimeoutError:
            logger.info(
                f"[expression] no pick within {self.timeout_seconds}s: '{line[:30]}'"
            )
            return None
        except Exception as error:
            logger.warning(
                f"[expression] pick failed ({type(error).__name__}: {error})"
            )
            return None
        picked = pick_actions(line, self.expressions, list(self.motions), raw)
        logger.debug(
            f"[expression] {picked} in {time.monotonic() - started:.2f}s: '{line[:30]}'"
        )
        return picked


def _client(character: Any):
    return background_client(
        character, max_tokens=MAX_TOKENS, timeout_seconds=TIMEOUT_SECONDS + 0.5
    )


def uses_background_expressions(character: Any) -> bool:
    """這個角色的表情真的由背景模型挑：選了 background，而且有背景模型。"""
    if getattr(character, "expression_source", "tags") != "background":
        return False
    return _client(character) is not None


def picker_for(
    character: Any, live2d_model: Any, agent: Any = None
) -> Optional[ExpressionPicker]:
    """這一則回覆用的挑選器；tags 模式、沒有背景模型、模型沒得挑時是 None。"""
    if getattr(character, "expression_source", "tags") != "background":
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
    client = _client(character)
    if client is None:
        return None
    read_mood = getattr(agent, "mood_message", None)
    return ExpressionPicker(
        client=client,
        expressions=expressions,
        motions=motions,
        mood=read_mood if callable(read_mood) else (lambda: None),
    )


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
