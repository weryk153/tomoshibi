"""換角色模型時，跟著換成那個模型的預設人設。

選 3D 時角色應該是 Shino，而不是繼續講「住在螢幕上的 AI 夥伴」那份通用人設。但使用者
自己寫的人設絕對不能被蓋掉，所以只在「人設還是某一份預設、沒被改過」時才換。預設有兩種：

- 模型資料夾裡的 persona.yaml（例如 vrm-models/Sendagaya_Shino/persona.yaml）
- 範本 conf.tomoshibi.default.yaml 裡的通用人設

換到沒有 persona.yaml 的模型（例如內建的 Live2D）時，退回通用人設。比對時忽略頭尾空白與
行尾空白，編輯器存檔時補的換行不會讓人設被當成「改過」。
"""

from __future__ import annotations

import os

import yaml

TEMPLATE_PATH = os.path.join("config_templates", "conf.tomoshibi.default.yaml")
MODEL_ROOTS = ("vrm-models", "live2d-models")
PERSONA_FILENAME = "persona.yaml"


def _normalize(text: object) -> str:
    return "\n".join(line.rstrip() for line in str(text or "").strip().splitlines())


def _load(path: str) -> dict | None:
    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except (OSError, yaml.YAMLError):
        return None
    return data if isinstance(data, dict) else None


def _persona(data: dict | None) -> dict | None:
    if not data:
        return None
    prompt = data.get("persona_prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        return None
    name = data.get("character_name")
    return {
        "character_name": name if isinstance(name, str) and name.strip() else None,
        "persona_prompt": prompt,
    }


def template_default() -> dict | None:
    """範本裡的通用人設。"""
    data = _load(TEMPLATE_PATH) or {}
    return _persona(data.get("character_config") or {})


def model_default(model_name: object) -> dict | None:
    """模型資料夾裡的 persona.yaml；沒有就回 None。"""
    name = str(model_name or "")
    # 模型名稱會拼進路徑，只接受單一層的資料夾名稱。
    if not name or name.startswith(".") or os.path.basename(name) != name:
        return None
    for root in MODEL_ROOTS:
        persona = _persona(_load(os.path.join(root, name, PERSONA_FILENAME)))
        if persona:
            return persona
    return None


def swap_for_model_change(
    old_model: object,
    new_model: object,
    persona_prompt: str,
    character_name: str | None,
) -> tuple[str, str | None, bool]:
    """回傳 (persona_prompt, character_name, 是否換了)。

    模型沒變、或人設不是任何一份預設（使用者改過）時原樣回傳。
    顯示名稱只在它也還是預設（或空）時才跟著換。
    """
    if not new_model or old_model == new_model:
        return persona_prompt, character_name, False

    known = [d for d in (template_default(), model_default(old_model)) if d]
    if _normalize(persona_prompt) not in {
        _normalize(d["persona_prompt"]) for d in known
    }:
        return persona_prompt, character_name, False

    target = model_default(new_model) or template_default()
    if target is None:
        return persona_prompt, character_name, False

    known_names = {d["character_name"] for d in known if d["character_name"]}
    name = character_name
    if not character_name or character_name in known_names:
        name = target["character_name"] or character_name
    return target["persona_prompt"], name, True
